# FT Article Scraper API

A lightweight FastAPI server for scraping and prioritizing Financial Times articles.

## Features

- Persistent FT login session management
- Article scraping with automatic session refresh
- Article prioritization based on geopolitical keywords
- CORS support for iOS client integration
- Low memory footprint
- Docker support

## Requirements

- Python 3.11+
- Chrome/Chromium browser
- ChromeDriver

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Edit `.env` and add your FT credentials:
```
FT_USERNAME=your_username
FT_UNI_ID=your_uni_id
FT_PASSWORD=your_password
```

## Running the Server

### Local Development

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Using Docker

```bash
docker build -t ft-scraper .
docker run -p 8000:8000 ft-scraper
```

## API Endpoints

### Initialize Scraper
```bash
POST /initialize
Content-Type: application/json

{
    "username": "your_username",
    "uni_id": "your_uni_id",
    "password": "your_password"
}
```

### Get Article List
```bash
GET /articles
```

### Get Full Article
```bash
GET /article/{url}
```

### Get Prioritized Articles
```bash
GET /prioritize-articles
```

## Response Format

```json
{
    "headline": "Article Title",
    "url": "https://ft.com/article-url",
    "standfirst": "Article summary",
    "full_text": "Full article content",
    "author": "Author name",
    "date": "Publication date",
    "priority_score": 0.85,
    "tags": ["tag1", "tag2"]
}
```

## Memory Optimization

The server is optimized for low memory usage by:
- Removing audio processing and TTS functionality
- Eliminating in-memory caching
- Using streaming responses where possible
- Implementing proper cleanup on shutdown

## Development

### Project Structure
```
.
├── main.py              # FastAPI application
├── scraper.py           # FT scraping logic
├── prioritizator.py     # Article prioritization
├── requirements.txt     # Python dependencies
├── Dockerfile          # Docker configuration
└── .env                # Environment variables
```

### Adding New Features

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

[Your License]
