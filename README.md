# CineWorld – Cloud-based Movie Review Web Service

CineWorld is a cloud-based movie review web service that allows users to browse movies, view box office data, and write reviews with images.  
This project was designed and deployed on AWS to gain **hands-on experience in backend development, cloud infrastructure, and service operations**, with a focus on **security, data separation, and operational clarity**.

---

## Key Features

- Browse popular and box office movies  
- Movie detail pages powered by external APIs  
- User reviews and ratings  
- Image upload and storage using **Amazon S3**  
- Review text and metadata stored in **Amazon RDS (MySQL)**  
- Google OAuth authentication (Django Allauth)  
- REST API support for extensibility  

---

## Tech Stack

### Backend
- Python, Django  
- Django REST Framework  

### Cloud & Infrastructure
- **AWS EC2 (Elastic IP)** – application server  
- **AWS RDS (MySQL)** – relational database for reviews  
- **AWS S3** – object storage for user-uploaded images  
- Nginx & Gunicorn – production-grade deployment  
- Linux (Ubuntu)  

### External APIs
- TMDB (The Movie Database)  
- KOBIS (Korean Box Office Information System)  

---

## Architecture Overview

### High-level Architecture
- Users access the service via **Elastic IP** attached to an EC2 instance  
- The Django application:
  - Fetches movie and box office data from **external APIs (TMDB, KOBIS)**  
  - Stores review text and relational data in **Amazon RDS**  
  - Uploads and retrieves review images from **Amazon S3**  
- Static and media assets are decoupled from the application server  

### Data Flow
1. User requests movie or detail page  
2. Django backend calls external movie APIs and renders data  
3. When a review is submitted:
   - Text content → **RDS (MySQL)**  
   - Image file → **S3**  
4. The frontend displays review text from RDS and images via S3 URLs  

---

## Security & Configuration

- No secrets or credentials are stored in the repository  
- All sensitive values are injected via **environment variables**  
- Production environment uses:
  - `DEBUG = False`
  - Restricted `ALLOWED_HOSTS`
- AWS resources are isolated by responsibility:
  - **EC2** – application logic  
  - **RDS** – relational data  
  - **S3** – binary/media data  
- AWS credentials are handled via **environment variables or IAM Role**  
- Public repository is safe by design  

### Example Environment Variables
```env
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
