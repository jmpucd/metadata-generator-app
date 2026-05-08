"""
app/dagster/triggers.py
Placeholder schedule and sensor definitions.
Uncomment and import into definitions.py when the trigger pattern is decided.
"""
# from dagster import (
#     RunRequest,
#     ScheduleDefinition,
#     SensorEvaluationContext,
#     sensor,
#     define_asset_job,
# )
# from app.dagster.jobs import ingest_and_generate_job
# from app.config import IMAGES_DIR
# import os

# ── Option A: nightly schedule ────────────────────────────────────────────────
# nightly_ingest_schedule = ScheduleDefinition(
#     job=ingest_and_generate_job,
#     cron_schedule="0 2 * * *",   # 2 AM every night
#     run_config={
#         "ops": {
#             "ingested_images": {
#                 "config": {
#                     "image_folder": str(IMAGES_DIR),
#                     "collection_name": "default",
#                 }
#             }
#         }
#     },
# )

# ── Option B: file-system sensor (polls for new images) ──────────────────────
# @sensor(job=ingest_and_generate_job, minimum_interval_seconds=300)
# def new_image_sensor(context: SensorEvaluationContext):
#     """Fire when new images appear in IMAGES_DIR."""
#     image_dir = IMAGES_DIR
#     known_files = set(context.cursor.split(",")) if context.cursor else set()
#     current_files = {
#         str(p) for p in image_dir.rglob("*")
#         if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
#     }
#     new_files = current_files - known_files
#     if new_files:
#         context.update_cursor(",".join(current_files))
#         yield RunRequest(
#             run_key=str(sorted(new_files)),
#             run_config={
#                 "ops": {
#                     "ingested_images": {
#                         "config": {
#                             "image_folder": str(image_dir),
#                             "collection_name": "default",
#                         }
#                     }
#                 }
#             },
#         )
