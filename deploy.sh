#!/bin/bash

# VocaLearn Backend Deployment Script
# Simplified version for standalone Django app with ffmpeg

set -e

echo "🚀 Starting VocaLearn Backend Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Creating from template..."
    cp .env.docker .env
    print_warning "Please update the .env file with your Azure AI service keys."
    print_warning "The app will use SQLite database by default - no additional database setup needed."
    read -p "Press Enter to continue after updating .env file..."
fi

# Create media and static directories
print_status "Creating media and static directories..."
mkdir -p media static

# Build and start container
print_status "Building Docker image..."
docker-compose build

print_status "Starting VocaLearn backend..."
docker-compose up -d

# Wait for container to be ready
print_status "Waiting for container to be ready..."
sleep 5

# Run migrations
print_status "Running database migrations..."
docker-compose exec web python manage.py migrate

# Collect static files
print_status "Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

# Create superuser (optional)
read -p "Do you want to create a superuser? (y/N): " create_superuser
if [[ $create_superuser =~ ^[Yy]$ ]]; then
    print_status "Creating superuser..."
    docker-compose exec web python manage.py createsuperuser
fi

# Check if service is running
print_status "Checking service status..."
docker-compose ps

# Test ffmpeg availability
print_status "Testing ffmpeg availability..."
docker-compose exec web ffmpeg -version | head -1

# Show logs
print_status "Showing recent logs..."
docker-compose logs --tail=10

print_status "✅ Deployment completed successfully!"
print_status "Your VocaLearn backend is now running at:"
print_status "  - Application: http://localhost:8000"
print_status "  - Admin: http://localhost:8000/admin"
print_status "  - API: http://localhost:8000/api/"

print_status "Features available:"
print_status "  ✓ ffmpeg for audio processing"
print_status "  ✓ Azure AI Services integration"
print_status "  ✓ Chinese text processing (jieba, zhon)"
print_status "  ✓ Audio format support (wav, mp3, ogg, m4a)"
print_status "  ✓ SQLite database (no external database needed)"

print_status "Useful commands:"
print_status "  - View logs: docker-compose logs -f"
print_status "  - Stop service: docker-compose down"
print_status "  - Restart service: docker-compose restart"
print_status "  - Access Django shell: docker-compose exec web python manage.py shell"
print_status "  - Test ffmpeg: docker-compose exec web ffmpeg -version"

echo ""
print_status "🎉 Happy coding with VocaLearn!"