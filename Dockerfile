# Start from a small official Python image
FROM python:3.11-slim

# Work inside the /app folder in the container
WORKDIR /app

# Copy only requirements first so Docker can cache the install step
COPY requirements.txt .

# Install the packages; no-cache keeps the image small
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project code
COPY . .

# Document the port the app listens on
EXPOSE 8000

# Start the server; 0.0.0.0 makes it reachable from outside the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]