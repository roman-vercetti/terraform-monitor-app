terraform {
  required_providers {
    docker = {
      source = "kreuzwerker/docker"
      version = "4.2.0"
    }
  }
}

provider "docker" {}

# Сети
resource "docker_network" "monitor_network" {
  name = "monitor-network"
}

# Тома
resource "docker_volume" "postgres_data" {
  name = "monitor-postgres-data"
}

resource "docker_volume" "redis_data" {
  name = "monitor-redis-data"
}

# PostgreSQL
resource "docker_image" "postgres" {
  name = "postgres:15-alpine"
}

resource "docker_container" "postgres" {
  name  = "monitor-postgres"
  image = docker_image.postgres.name
  env = [
    "POSTGRES_DB=monitor",
    "POSTGRES_USER=admin", 
    "POSTGRES_PASSWORD=secret"
  ]
  volumes {
    volume_name    = docker_volume.postgres_data.name
    container_path = "/var/lib/postgresql/data"
  }
  networks_advanced {
    name = docker_network.monitor_network.name
  }
  healthcheck {
    test = ["CMD-SHELL", "pg_isready -U admin -d monitor"]
    interval = "10s"
    timeout = "5s"
    retries = 5
  }
}

# Redis
resource "docker_image" "redis" {
  name = "redis:7-alpine"
}

resource "docker_container" "redis" {
  name    = "monitor-redis"
  image   = docker_image.redis.name
  command = ["redis-server", "--appendonly", "yes"]
  volumes {
    volume_name    = docker_volume.redis_data.name
    container_path = "/data"
  }
  networks_advanced {
    name = docker_network.monitor_network.name
  }
  healthcheck {
    test = ["CMD", "redis-cli", "ping"]
    interval = "10s"
    timeout = "5s" 
    retries = 5
  }
}

# Flask
resource "docker_image" "monitor_app" {
  name = "monitor-app:latest"
  build {
    context = "${path.module}/app"
    tag = ["monitor-app:latest"]
  }
  keep_locally = true
}

resource "docker_container" "monitor_app" {
  name  = "monitor-app"
  image = docker_image.monitor_app.name
  
  ports {
    internal = 5000
    external = 8080
  }
  
  env = [
    "DB_HOST=monitor-postgres",
    "DB_NAME=monitor", 
    "DB_USER=admin",
    "DB_PASSWORD=secret",
    "REDIS_HOST=monitor-redis",
    "REDIS_PORT=6379"
  ]
  
  networks_advanced {
    name = docker_network.monitor_network.name
  }
  
  depends_on = [
    docker_container.postgres,
    docker_container.redis
  ]
  
  restart = "unless-stopped"
}

output "app_url" {
  value = "http://localhost:8080"
}

output "check_postgres" {
  value = "docker exec -it monitor-postgres psql -U admin -d monitor -c 'SELECT * FROM websites;'"
}
