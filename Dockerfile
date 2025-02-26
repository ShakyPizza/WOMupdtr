# Use Python 3.10 (or your version)
FROM python:3.10

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Upgrade pip
RUN pip install --upgrade pip

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Cloud Run's expected port (even if unused)
ENV PORT=8080
# Run the bot
CMD ["python", "WOM.py"]
