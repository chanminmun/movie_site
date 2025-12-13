# CineWorld – Cloud-based Movie Review Web Service

## Overview
CineWorld is a cloud-based web application that allows users to browse movies, view box office data, and share reviews.
The project was built to gain hands-on experience with **AWS cloud infrastructure, backend development, and service operations**.

## Key Features
- Browse popular and box office movies
- Movie detail pages with external API data
- User reviews and ratings
- Image upload and storage using Amazon S3
- Authentication using Django Allauth (Google OAuth)
- REST API support for extensibility

## Tech Stack

### Backend
- Python, Django
- Django REST Framework

### Cloud & Infrastructure
- AWS EC2 – application server
- AWS RDS (MySQL) – relational database
- AWS S3 – media storage for user-uploaded images
- Nginx & Gunicorn – production-grade deployment
- Linux (Ubuntu)

### External APIs
- TMDB (The Movie Database)
- KOBIS (Korean Box Office Information System)

## Architecture Overview
- Django application deployed on AWS EC2
- MySQL database hosted on AWS RDS
- Media files served from AWS S3
- Environment variables used for all secrets and credentials
- Separation of development and production configurations

## Security & Configuration
- No secrets or credentials are stored in the repository
- All sensitive values are injected via environment variables
- Public repository is safe by design
- AWS credentials are handled via environment variables or IAM roles

### Example Environment Variables
```bash
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=

DB_ENGINE=mysql
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=

AWS_STORAGE_BUCKET_NAME=
AWS_S3_REGION_NAME=

TMDB_BEARER_TOKEN=
KOBIS_API_KEY=
Local Development
bash'''
코드 복사
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
Deployment Notes
Designed for deployment on AWS EC2

Static and media files can be served via Amazon S3

Production settings use DEBUG=False and restricted ALLOWED_HOSTS

Suitable for further extension with CI/CD pipelines or load balancing

Project Motivation
This project focuses on:

Understanding cloud-based application architecture

Operating a backend service from a customer and service perspective

Gaining practical experience relevant to AWS Professional Services and cloud engineering roles

Author
Chan Min Mun
GitHub: https://github.com/chanminmun
