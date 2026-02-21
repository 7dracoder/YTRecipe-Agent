import redis
import os
from rq import Queue
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

r = redis.Redis.from_url(os.getenv("REDIS_URL"))

# ── Dedicated queue per pipeline stage ────────────────────────
transcript_queue = Queue("transcript", connection=r)
extraction_queue = Queue("extraction", connection=r)
normalizer_queue = Queue("normalizer", connection=r)
cart_queue       = Queue("cart",       connection=r)
nutrition_queue  = Queue("nutrition",  connection=r)
recipe_queue     = Queue("recipe",     connection=r)


def enqueue_job(queue: Queue, func, *args, **kwargs):
    """
    Safely enqueue a job with error handling.
    Returns the job object.
    """
    try:
        job = queue.enqueue(func, *args, **kwargs)
        logger.info(f"📬 Job enqueued → Queue: '{queue.name}' | ID: {job.id}")
        return job
    except Exception as e:
        logger.error(f"❌ Failed to enqueue job: {e}")
        raise


def get_job_status(job_id: str) -> dict:
    """Check status of any queued job by ID."""
    from rq.job import Job
    try:
        job = Job.fetch(job_id, connection=r)
        return {
            "id": job.id,
            "status": job.get_status(),
            "result": job.result,
            "error": job.exc_info
        }
    except Exception as e:
        return {"error": str(e)}
