FROM python:3.12-slim

WORKDIR /app

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY gateway/ .
COPY proto/health_export.proto /tmp/proto/health_export.proto
RUN python -m grpc_tools.protoc \
    -I/tmp/proto \
    --python_out=. \
    --grpc_python_out=. \
    /tmp/proto/health_export.proto

RUN mkdir -p /data

EXPOSE 50051

CMD ["python", "server.py"]