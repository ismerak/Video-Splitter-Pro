#!/usr/bin/env python3
import os, json, subprocess, uuid, threading, tempfile, platform
from flask import Flask, request, send_file, jsonify, Response, send_from_directory
from pathlib import Path

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

# ---- Cross-platform temp paths ----
if platform.system() == 'Windows':
    _BASE = Path(tempfile.gettempdir()) / 'vsp'
else:
    _BASE = Path('/tmp')

UPLOAD_DIR = _BASE / 'vsp_uploads'
OUTPUT_DIR = _BASE / 'vsp_outputs'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

jobs = {}

CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
}

@app.after_request
def add_cors(resp):
    for k, v in CORS_HEADERS.items():
        resp.headers[k] = v
    return resp

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def options(path=''):
    return Response('', 204, CORS_HEADERS)

# ---- Serve frontend HTML ----
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# ---- Probe video metadata ----
@app.route('/probe', methods=['POST'])
def probe():
    f = request.files.get('video')
    if not f:
        return jsonify({'error': 'No file uploaded'}), 400
    suffix = Path(f.filename).suffix or '.mp4'
    tmp = UPLOAD_DIR / f'{uuid.uuid4()}{suffix}'
    f.save(tmp)
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
               '-show_streams', '-show_format', str(tmp)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise Exception('ffprobe error: ' + r.stderr[:300])
        data = json.loads(r.stdout)
        duration = float(data['format']['duration'])
        size = int(data['format']['size'])
        vs = next((s for s in data['streams'] if s['codec_type'] == 'video'), {})
        return jsonify({
            'duration': duration, 'size': size,
            'width': vs.get('width', 0), 'height': vs.get('height', 0),
            'path': str(tmp)
        })
    except Exception as e:
        tmp.unlink(missing_ok=True)
        return jsonify({'error': str(e)}), 500

# ---- Start split job ----
@app.route('/split', methods=['POST'])
def split():
    data = request.json or {}
    video_path   = data.get('path')
    segment_dur  = float(data.get('segmentDuration', 60))
    speed        = float(data.get('speed', 1.0))
    ratio        = data.get('ratio', '9:16')
    duration     = float(data.get('duration', 0))

    if not video_path or not Path(video_path).exists():
        return jsonify({'error': 'Video not found on server'}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {'status': 'running', 'progress': 0, 'message': 'Starting...', 'segments': []}
    threading.Thread(target=do_split,
                     args=(job_id, video_path, segment_dur, speed, ratio, duration),
                     daemon=True).start()
    return jsonify({'job_id': job_id})

def build_filters(ratio, speed):
    vf_parts, af_parts = [], []
    scale_map = {
        '9:16': 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920',
        '16:9': 'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080',
        '1:1':  'scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080',
    }
    if ratio in scale_map:
        vf_parts.append(scale_map[ratio])
    if speed != 1.0:
        vf_parts.append(f'setpts={1/speed:.6f}*PTS')
        s = speed
        chain = []
        while s < 0.5:  chain.append('atempo=0.5'); s /= 0.5
        while s > 2.0:  chain.append('atempo=2.0'); s /= 2.0
        chain.append(f'atempo={s:.6f}')
        af_parts.append(','.join(chain))
    return (','.join(vf_parts) or None, ','.join(af_parts) or None)

def do_split(job_id, video_path, segment_dur, speed, ratio, total_dur):
    try:
        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        base_name = Path(video_path).stem
        n_segs = max(1, -(-int(total_dur) // int(segment_dur)))
        jobs[job_id]['message'] = f'Processing {n_segs} segments...'
        vf, af = build_filters(ratio, speed)
        segments = []
        for i in range(n_segs):
            start = i * segment_dur
            end   = min(start + segment_dur, total_dur)
            out   = job_dir / f'{base_name}_part{i+1:02d}.mp4'
            cmd = ['ffmpeg', '-y', '-ss', str(start), '-i', video_path, '-t', str(end - start)]
            if vf: cmd += ['-vf', vf]
            if af: cmd += ['-af', af]
            cmd += ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                    '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if out.exists():
                segments.append({
                    'index': i+1, 'start': start, 'end': end,
                    'duration': end - start, 'filename': out.name,
                    'size': out.stat().st_size,
                    'download_url': f'/download/{job_id}/{out.name}'
                })
            else:
                jobs[job_id]['message'] = f'Segment {i+1} error: {proc.stderr[-150:]}'
            jobs[job_id]['progress'] = int(((i+1) / n_segs) * 100)
            jobs[job_id]['segments'] = segments
        jobs[job_id].update(status='done', progress=100,
                            message=f'Done! {len(segments)} segments ready.')
    except Exception as e:
        jobs[job_id].update(status='error', message=str(e))

@app.route('/status/<job_id>')
def status(job_id):
    j = jobs.get(job_id)
    return jsonify(j) if j else (jsonify({'error': 'Not found'}), 404)

@app.route('/download/<job_id>/<filename>')
def download(job_id, filename):
    path = OUTPUT_DIR / job_id / filename
    if not path.exists():
        return jsonify({'error': 'File not found'}), 404
    return send_file(str(path), as_attachment=True, download_name=filename)

@app.route('/ping')
def ping():
    ok = subprocess.run(['ffmpeg', '-version'], capture_output=True).returncode == 0
    return jsonify({'ok': True, 'ffmpeg': ok})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7788))
    print(f'🚀 Video Splitter Pro — http://0.0.0.0:{port}')
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
