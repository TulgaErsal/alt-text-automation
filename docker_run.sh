docker run --rm -p 5000:5000 -p 6080:6080 \
  -e SECRET_KEY=test-secret \
  -e GOOGLE_CLIENT_ID=your-client-id \
  -e GOOGLE_CLIENT_SECRET=your-client-secret \
  alt-text-automation
