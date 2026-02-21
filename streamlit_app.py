import os
import streamlit as st
import json
from dotenv import load_dotenv
from utils.config import get_secret

load_dotenv()

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="YTRecipe Agent",
    page_icon="🍳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── CSS ───────────────────────────────────────────────────────
def load_css():
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ── Session State ─────────────────────────────────────────────
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = {}
if "recipe_done" not in st.session_state:
    st.session_state.recipe_done = False
if "user_id" not in st.session_state:
    st.session_state.user_id = "default_user"

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.image("https://em-content.zobj.net/source/apple/391/cooking_1f373.png", width=60)
    st.title("Recipe Agent")
    st.caption("YouTube → Groceries → Recipe")
    st.divider()

    st.subheader("Your Preferences")

    dietary = st.multiselect(
        "Dietary Restrictions",
        ["Vegetarian", "Vegan", "Gluten-Free",
         "Dairy-Free", "Keto", "Paleo", "Halal", "Kosher"],
        help="Claude will adjust ingredient selection based on these"
    )
    allergies = st.multiselect(
        "Allergies",
        ["Peanuts", "Tree Nuts", "Shellfish", "Fish",
         "Eggs", "Milk", "Soy", "Wheat"],
    )
    prefer_organic = st.toggle("Prefer Organic Products", value=False)
    servings       = st.slider("Default Servings", 1, 12, 4)

    st.divider()
    st.subheader("⚙️ Settings")
    show_raw_json = st.toggle("Show Raw JSON Output", value=False)

    if st.button("💾 Save Preferences", use_container_width=True):
        try:
            from app_redis.state import save_user_preferences
            save_user_preferences(st.session_state.user_id, {
                "dietary":        dietary,
                "allergies":      allergies,
                "prefer_organic": prefer_organic,
                "servings":       servings
            })
            st.success("✅ Preferences saved!")
        except Exception as e:
            st.warning(f"Could not save: {e}")

    if st.button("🗑️ Clear Cache", use_container_width=True):
        try:
            from app_redis.state import r
            r.flushdb()
            st.session_state.recipe_done = False
            st.session_state.pipeline_results = {}
            st.success("✅ Cache cleared!")
        except Exception as e:
            st.warning(f"Could not clear cache: {e}")

    st.divider()
    with st.expander("🔑 Secrets Diagnostics"):
        required = {
            "ANTHROPIC_API_KEY": "Claude AI",
            "USDA_API_KEY":      "Nutrition",
            "KROGER_CLIENT_ID":  "Grocery",
            "REDIS_URL":         "Cache",
        }
        for k, label in required.items():
            val = get_secret(k)
            if val:
                st.success(f"✅ {label} (`{k}`)")
            else:
                st.error(f"❌ {label} (`{k}`) — MISSING")

    st.caption("Built with Love!")

# ── Header ────────────────────────────────────────────────────
st.title("🍳 YTRecipe Agent")
st.caption("Paste a cooking video URL → Get ingredients, grocery cart & full recipe")

col1, col2 = st.columns([4, 1])
with col1:
    youtube_url = st.text_input(
        "YouTube URL",
        placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed"
    )
with col2:
    run_button = st.button("Give it to me!!!", use_container_width=True, type="primary")

st.divider()

# ── Pipeline Step Indicator ───────────────────────────────────
def show_pipeline_steps(current=None, completed=[]):
    steps = [
        ("📝", "Transcript",    "transcript_extracted"),
        ("🤖", "Extraction",    "ingredients_extracted"),
        ("🔧", "Normalization", "ingredients_normalized"),
        ("🛒", "Cart",          "instacart_mapped"),
        ("🥗", "Nutrition",     "nutrition_calculated"),
        ("📖", "Recipe",        "recipe_generated"),
    ]
    cols = st.columns(len(steps))
    for i, (icon, label, key) in enumerate(steps):
        with cols[i]:
            if key in completed:
                st.markdown(f'<div class="pipeline-step step-done">{icon} {label} ✓</div>', unsafe_allow_html=True)
            elif key == current:
                st.markdown(f'<div class="pipeline-step step-running">{icon} {label} ⟳</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="pipeline-step step-pending">{icon} {label}</div>', unsafe_allow_html=True)

# ── Pipeline Runner ───────────────────────────────────────────
if run_button and youtube_url:
    if not youtube_url.startswith("http"):
        st.error("❌ Please enter a valid YouTube URL")
    elif not get_secret("ANTHROPIC_API_KEY"):
        st.error(
            "**ANTHROPIC_API_KEY is missing.** "
            "Go to Streamlit app → Settings → Secrets and add:\n\n"
            "```toml\nANTHROPIC_API_KEY = \"sk-ant-...\"\n```"
        )
    else:
        completed_steps = []
        results         = {}

        progress_placeholder = st.empty()
        status_placeholder   = st.empty()

        # Step 1: Transcript
        with progress_placeholder.container():
            show_pipeline_steps("transcript_extracted", completed_steps)
        status_placeholder.info("📝 Extracting transcript from YouTube...")
        try:
            from utils.helpers import extract_video_id
            from services.transcript import get_transcript
            video_id   = extract_video_id(youtube_url)
            transcript = get_transcript(video_id)
            results["transcript"] = transcript
            completed_steps.append("transcript_extracted")
            status_placeholder.success(f"✅ Transcript extracted — {len(transcript.get('text', ''))} characters")
        except Exception as e:
            st.error(f"❌ Transcript failed: {e}")
            st.stop()

        # Step 2: Extraction
        with progress_placeholder.container():
            show_pipeline_steps("ingredients_extracted", completed_steps)
        status_placeholder.info("🤖 Claude extracting ingredients...")
        try:
            from agents.extractor import run_extraction
            extracted = run_extraction(results["transcript"])
            results["extracted"] = extracted
            completed_steps.append("ingredients_extracted")
            status_placeholder.success(f"✅ Found {len(extracted.get('ingredients', []))} ingredients")
        except Exception as e:
            st.error(f"❌ Extraction failed: {e}")
            st.stop()

        # Step 3: Normalization
        with progress_placeholder.container():
            show_pipeline_steps("ingredients_normalized", completed_steps)
        status_placeholder.info("🔧 Normalizing ingredients...")
        try:
            from agents.normalizer import run_normalization
            normalized = run_normalization(results["extracted"])
            results["normalized"] = normalized
            completed_steps.append("ingredients_normalized")
            status_placeholder.success("✅ Ingredients normalized")
        except Exception as e:
            st.error(f"❌ Normalization failed: {e}")
            st.stop()

        # Step 4: Cart Mapping
        with progress_placeholder.container():
            show_pipeline_steps("instacart_mapped", completed_steps)
        status_placeholder.info("🛒 Finding grocery products...")
        try:
            from agents.cart_agent import run_cart_mapping
            cart = run_cart_mapping(results["normalized"], user_id=st.session_state.user_id)
            results["cart"] = cart
            completed_steps.append("instacart_mapped")
            status_placeholder.success(
                f"✅ Cart ready — {len(cart.get('cart', []))} items, est. ${cart.get('estimated_total', 0):.2f}"
            )
        except Exception as e:
            st.error(f"❌ Cart mapping failed: {e}")
            st.stop()

        # Step 5: Nutrition
        with progress_placeholder.container():
            show_pipeline_steps("nutrition_calculated", completed_steps)
        status_placeholder.info("🥗 Calculating nutrition data...")
        try:
            from services.nutrition import get_nutrition_data
            nutrition = get_nutrition_data(results["normalized"].get("normalized", []))
            results["nutrition"] = nutrition
            completed_steps.append("nutrition_calculated")
            status_placeholder.success(f"✅ Nutrition calculated — ~{nutrition.get('total_calories', 0):.0f} total kcal")
        except Exception as e:
            st.error(f"❌ Nutrition failed: {e}")
            st.stop()

        # Step 6: Recipe
        with progress_placeholder.container():
            show_pipeline_steps("recipe_generated", completed_steps)
        status_placeholder.info("📖 Claude composing final recipe...")
        try:
            from agents.recipe_composer import run_recipe_composition
            recipe = run_recipe_composition(
                transcript=results["transcript"],
                ingredients=results["normalized"],
                nutrition=results["nutrition"]
            )
            results["recipe"] = recipe
            completed_steps.append("recipe_generated")
            status_placeholder.success("✅ Recipe generated!")
        except Exception as e:
            st.error(f"❌ Recipe generation failed: {e}")
            st.stop()

        # Done — persist to session state
        with progress_placeholder.container():
            show_pipeline_steps(None, completed_steps)
        status_placeholder.empty()
        st.session_state.pipeline_results = results
        st.session_state.recipe_done      = True
        st.balloons()

# ── Results Display ───────────────────────────────────────────
if st.session_state.recipe_done and st.session_state.pipeline_results:
    results   = st.session_state.pipeline_results
    recipe    = results.get("recipe", {}).get("recipe", {})
    cart      = results.get("cart", {})
    nutrition = results.get("nutrition", {})

    tab1, tab2, tab3, tab4 = st.tabs(["📖 Recipe", "🛒 Grocery Cart", "🥗 Nutrition", "🔍 Raw Data"])

    # ── Tab 1: Recipe ─────────────────────────────────────────
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("⏱ Prep",      f"{recipe.get('prep_time_minutes', '?')} min")
        c2.metric("🔥 Cook",      f"{recipe.get('cook_time_minutes', '?')} min")
        c3.metric("🍽 Servings",  recipe.get("servings", "?"))
        c4.metric("🔥 Calories",  f"{recipe.get('calories_per_serving', '?')} kcal")

        st.divider()
        st.subheader(f"🍳 {recipe.get('name', 'Recipe')}")

        st.markdown("### 🧾 Ingredients")
        ingredients = recipe.get("ingredients", [])
        ing_cols = st.columns(2)
        half = max(len(ingredients) // 2, 1)
        for i, ing in enumerate(ingredients):
            with ing_cols[0] if i < half else ing_cols[1]:
                if isinstance(ing, dict):
                    qty  = ing.get("quantity", "")
                    unit = ing.get("unit", "")
                    name = (ing.get("name") or ing.get("ingredient")
                            or ing.get("normalized_name") or ing.get("item") or "")
                    opt  = " *(optional)*" if ing.get("optional") else ""
                    parts = " ".join(filter(None, [str(qty), str(unit), name])).strip()
                    st.markdown(f"- {parts}{opt}")
                else:
                    st.markdown(f"- {ing}")

        st.markdown("### 👨‍🍳 Instructions")
        for i, step in enumerate(recipe.get("instructions", []), 1):
            st.markdown(f'<div class="step-card">**Step {i}** — {step}</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("### 📦 Storage")
            st.info(recipe.get("storage", "N/A"))
        with col2:
            st.markdown("### 🍽 Serving Suggestions")
            st.info(recipe.get("serving_suggestions", "N/A"))

        st.divider()
        st.download_button(
            "⬇️ Download Recipe JSON",
            data=json.dumps(results.get("recipe", {}), indent=2),
            file_name=f"{recipe.get('name', 'recipe').replace(' ', '_')}.json",
            mime="application/json",
            use_container_width=True
        )

    # ── Tab 2: Grocery Cart ───────────────────────────────────
    with tab2:
        cart_items = cart.get("cart", [])
        missing    = cart.get("missing_items", [])
        total      = cart.get("estimated_total", 0)

        c1, c2, c3 = st.columns(3)
        c1.metric("🛒 Items in Cart",    len(cart_items))
        c2.metric("💰 Estimated Total",  f"${total:.2f}")
        c3.metric("⚠️ Missing Items",    len(missing))

        st.divider()
        st.subheader("✅ Found Items")
        for item in cart_items:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{item.get('ingredient', '')}** → {item.get('selected_product', '')}")
                st.caption(item.get("reason", ""))
            with col2:
                st.markdown(f"📦 `{item.get('source', 'kroger')}`")
            with col3:
                price = item.get("price")
                st.markdown(f"**${float(price):.2f}**" if price else "Price N/A")
            st.divider()

        if missing:
            st.subheader("⚠️ Not Found")
            for m in missing:
                st.warning(f"**{m.get('ingredient', '')}** — {m.get('reason', 'Not found')}")

    # ── Tab 3: Nutrition ──────────────────────────────────────
    with tab3:
        nut_items = nutrition.get("ingredients", [])
        servings_count = max(recipe.get("servings", 1) or 1, 1)
        total_cals     = nutrition.get("total_calories", 0)

        c1, c2, c3 = st.columns(3)
        c1.metric("🔥 Total Calories",     f"{total_cals:.0f} kcal")
        c2.metric("🍽 Per Serving",         f"{total_cals / servings_count:.0f} kcal")
        c3.metric("🥗 Ingredients Tracked", len(nut_items))

        st.divider()
        st.subheader("Per Ingredient Breakdown")
        for nut in nut_items:
            with st.expander(f"🥄 {nut.get('ingredient', '')}"):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calories", f"{nut.get('calories_per_100g') or 0:.0f} kcal")
                c2.metric("Protein",  f"{nut.get('protein_g') or 0:.1f}g")
                c3.metric("Carbs",    f"{nut.get('carbs_g') or 0:.1f}g")
                c4.metric("Fat",      f"{nut.get('fat_g') or 0:.1f}g")

    # ── Tab 4: Raw Data ───────────────────────────────────────
    with tab4:
        st.subheader("🔍 Raw Pipeline Output")
        with st.expander("📝 Transcript"):
            st.text(results.get("transcript", {}).get("text", "")[:2000] + "...")
        with st.expander("🤖 Extracted Ingredients"):
            st.json(results.get("extracted", {}))
        with st.expander("🔧 Normalized Ingredients"):
            st.json(results.get("normalized", {}))
        with st.expander("🛒 Cart Data"):
            st.json(results.get("cart", {}))
        with st.expander("🥗 Nutrition Data"):
            st.json(results.get("nutrition", {}))
        with st.expander("📖 Final Recipe"):
            st.json(results.get("recipe", {}))
