FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN useradd --create-home --uid 10001 fde && mkdir -p /app/outputs/stage-11 && chown -R fde:fde /app/outputs
USER fde
EXPOSE 8781
CMD ["python3", "stage11_stack.py", "--host", "0.0.0.0"]
