"""FastAPI app for running feasibility scans."""

from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

from .config import settings
from .queue import get_queue
from .schemas import ScanRequest
from .storage import init_db, create_scan, get_scan, list_scans


BASE_DIR = Path(__file__).resolve().parents[1]
WEB_DIST = BASE_DIR / 'web' / 'dist'

app = FastAPI(title='Pendo Feasibility Scraper')
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)


def get_current_user(request) -> dict:
    """Get the authenticated user from session."""
    user = request.session.get('user')
    if not user:
        raise HTTPException(status_code=401, detail='Not authenticated')
    return user


@app.on_event('startup')
def on_startup() -> None:
    """Initialize DB on startup."""
    init_db()


@app.get('/health')
def health() -> dict:
    """Health check."""
    return {'status': 'ok'}


@app.get('/auth/login')
async def auth_login(request):
    """Start Google OAuth flow."""
    if not settings.google_redirect_uri:
        raise HTTPException(status_code=500, detail='Missing redirect URI')
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get('/auth/callback')
async def auth_callback(request):
    """Handle Google OAuth callback."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if not userinfo:
        raise HTTPException(status_code=401, detail='No user info from Google')
    email = userinfo.get('email', '')
    domain = email.split('@')[-1].lower() if '@' in email else ''
    if settings.allowed_google_domain and domain != settings.allowed_google_domain.lower():
        raise HTTPException(status_code=403, detail='Unauthorized domain')
    request.session['user'] = {
        'email': email,
        'name': userinfo.get('name', '')
    }
    return RedirectResponse('/')


@app.get('/auth/logout')
def auth_logout(request):
    """Clear session."""
    request.session.clear()
    return RedirectResponse('/')


@app.get('/api/me')
def api_me(request):
    """Current user info."""
    user = request.session.get('user')
    return user or {}


@app.post('/api/scans')
def create_scan_job(payload: ScanRequest, request):
    """Create a scan job."""
    get_current_user(request)
    scan_id = create_scan(payload.target_url, payload.config.model_dump())
    queue = get_queue()
    queue.enqueue(
        'worker.tasks.run_scan_task',
        scan_id,
        payload.model_dump(),
        job_timeout=60 * 30
    )
    return {'id': scan_id, 'status': 'queued'}


@app.get('/api/scans')
def scans_list(request):
    """List recent scans."""
    get_current_user(request)
    return list_scans()


@app.get('/api/scans/{scan_id}')
def scan_detail(scan_id: str, request):
    """Get scan status and metadata."""
    get_current_user(request)
    scan = get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail='Scan not found')
    return scan


@app.get('/api/scans/{scan_id}/report')
def scan_report(scan_id: str, request):
    """Get text report."""
    get_current_user(request)
    scan = get_scan(scan_id)
    if not scan or not scan.get('report_text_path'):
        raise HTTPException(status_code=404, detail='Report not found')
    return FileResponse(scan['report_text_path'], media_type='text/plain')


@app.get('/api/scans/{scan_id}/report.json')
def scan_report_json(scan_id: str, request):
    """Get JSON report."""
    get_current_user(request)
    scan = get_scan(scan_id)
    if not scan or not scan.get('report_json_path'):
        raise HTTPException(status_code=404, detail='Report not found')
    return FileResponse(scan['report_json_path'], media_type='application/json')


if WEB_DIST.exists():
    app.mount('/', StaticFiles(directory=str(WEB_DIST), html=True), name='web')
