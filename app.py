"""
Deck Engine API — Flask routes for deck generation.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file
from models.deck_config import DeckConfig
from engine.orchestrator import generate_deck, generate_deck_sync, get_job

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "deck-engine-api", "version": "0.1.0"})


@app.route("/api/decks/generate", methods=["POST"])
def api_generate_deck():
    """
    Start async deck generation. Returns a job ID to poll.

    POST body: DeckConfig JSON
    Returns: {"job_id": "abc123"}
    """
    try:
        data = request.get_json()
        config = DeckConfig(**data)
        job_id = generate_deck(config)
        return jsonify({"job_id": job_id, "status": "queued"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/decks/generate-sync", methods=["POST"])
def api_generate_deck_sync():
    """
    Synchronous deck generation. Blocks until the .pptx is ready, then returns the file.

    POST body: DeckConfig JSON
    Returns: .pptx file
    """
    try:
        data = request.get_json()
        config = DeckConfig(**data)
        pptx_bytes = generate_deck_sync(config)

        # Save temporarily
        from config import OUTPUT_DIR
        import uuid
        filename = f"{uuid.uuid4().hex[:8]}.pptx"
        filepath = OUTPUT_DIR / filename
        filepath.write_bytes(pptx_bytes)

        return send_file(
            filepath,
            mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            as_attachment=True,
            download_name=f"{config.title.replace(' ', '_')}.pptx",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/decks/<job_id>/status", methods=["GET"])
def api_job_status(job_id):
    """Poll the status of a generation job."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error": job.get("error"),
    })


@app.route("/api/decks/<job_id>/download", methods=["GET"])
def api_download_deck(job_id):
    """Download a completed deck."""
    job = get_job(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    if job["status"] != "complete":
        return jsonify({"error": f"Job not ready. Status: {job['status']}"}), 400

    filepath = Path(job["file_path"])
    if not filepath.exists():
        return jsonify({"error": "File not found"}), 404

    title = job["config"].get("title", "deck").replace(" ", "_")
    return send_file(
        filepath,
        mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        as_attachment=True,
        download_name=f"{title}.pptx",
    )


@app.route("/api/research/preview", methods=["POST"])
def api_research_preview():
    """Run research only and return the results."""
    try:
        data = request.get_json()
        from engine.researcher import research_for_deck, summarize_research
        research = research_for_deck(
            audience=data.get("audience", ""),
            industry=data.get("industry", ""),
            products=data.get("products", []),
            competitors=data.get("competitors", []),
            topic=data.get("topic", ""),
        )
        summary = summarize_research(research)
        return jsonify({"research": research, "summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/content/preview", methods=["POST"])
def api_content_preview():
    """Generate content for a slide sequence without building the .pptx."""
    try:
        data = request.get_json()
        from engine.content_writer import generate_slide_content
        slides = generate_slide_content(
            deck_title=data.get("title", ""),
            audience=data.get("audience", "Executive"),
            tone=data.get("tone", "Executive — concise, data-forward"),
            purpose=data.get("purpose", ""),
            key_messages=data.get("key_messages", []),
            layout_sequence=data.get("layout_sequence", [0, 3, 12, 12, 35]),
            research_summary=data.get("research_summary", ""),
            additional_context=data.get("additional_context", ""),
        )
        return jsonify({"slides": slides})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/media/generate", methods=["POST"])
def api_generate_media():
    """Generate a single image for a slide."""
    try:
        data = request.get_json()
        from engine.media_generator import generate_slide_image
        import uuid
        path = generate_slide_image(
            prompt=data.get("prompt", ""),
            slide_index=data.get("slide_index", 0),
            job_id=data.get("job_id", uuid.uuid4().hex[:8]),
        )
        if path:
            return send_file(path, mimetype="image/png")
        return jsonify({"error": "Image generation failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
