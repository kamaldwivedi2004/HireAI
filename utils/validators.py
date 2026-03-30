import re
from flask import current_app


def allowed_file(filename: str) -> bool:
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def validate_job_id(job_id) -> bool:
    if not job_id:
        return False
    return bool(re.match(r"^[A-Za-z0-9\-_]{3,40}$", str(job_id)))
