import os


def get_secret(key: str, default: str = None) -> str:
    """
    Read a config value from the first source that has it:
      1. os.environ  (local .env via load_dotenv, or system env)
      2. st.secrets  (Streamlit Cloud dashboard secrets)
      3. default
    Uses direct key access (st.secrets[key]) which is the only
    reliable method on Streamlit Community Cloud.
    """
    val = os.environ.get(key)
    if val:
        return val
    try:
        import streamlit as st
        val = st.secrets[key]
        if val is not None:
            # Cache into os.environ so subsequent calls are instant
            os.environ[key] = str(val)
            return str(val)
    except (KeyError, AttributeError, Exception):
        pass
    return default
