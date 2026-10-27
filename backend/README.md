# Backend - HealthHackathon 2025

Flask backend server for the HealthHackathon 2025 project.

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
```

2. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. (Optional) Copy `.env.example` to `.env` and configure as needed:
```bash
cp .env.example .env
```

## Running the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

## API Endpoints

- `GET /` - Welcome message
- `GET /api/health` - Health check endpoint
- `POST /api/example` - Example POST endpoint

## Development

To run in development mode with auto-reload, the app is already configured with `debug=True`.

