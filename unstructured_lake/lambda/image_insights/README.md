# Image Insights Lambda Function

## Overview
This Lambda function analyzes images using Claude's vision model to extract insights, detect forgeries, and decode QR codes.

## Dependencies

### Python Packages
- **boto3**: AWS SDK (from boto3 layer)
- **Pillow (PIL)**: Image processing for cropping QR codes (from pypdf layer)

## QR Code Detection

QR code detection and reading is handled by Claude's vision model:
- Claude detects QR codes in the image
- Claude attempts to read the QR code content directly
- Claude provides bounding box coordinates for the QR code location
- The Lambda function crops the QR code region and returns it as base64

### Key Features
- Detects QR codes using Claude vision
- Reads QR code content directly (when possible)
- Crops and returns QR code image with padding
- No external barcode libraries required

## Lambda Configuration

- **Runtime**: Python 3.12
- **Architecture**: x86_64 (required for Pillow/pyzbar compatibility)
- **Memory**: 2048 MB
- **Timeout**: 120 seconds
- **Layers**: 
  - pypdf layer (includes Pillow and pyzbar)
  - boto3 layer

## Environment Variables

- `REGION`: AWS region for Bedrock
- `VISION_MODEL_ID`: Claude vision model ID
- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)

## API Endpoint

**POST** `/image-insights/analyze`

### Request
```json
{
  "image": "base64_encoded_image_data",
  "prompt": "Optional custom analysis prompt"
}
```

### Response
```json
{
  "is_valid_image": true,
  "validation_message": "Image is valid",
  "key_insights": {
    "name": "John Doe",
    "age": "25-30",
    "document_type": "Driver's License",
    "other_details": ["Detail 1", "Detail 2"]
  },
  "forgery_detection": {
    "suspicious": false,
    "confidence": 0.95,
    "indicators": []
  },
  "qr_code_detected": true,
  "qr_bounding_box": {
    "x": 100,
    "y": 150,
    "width": 200,
    "height": 200
  },
  "qr_code_data": "https://example.com",
  "qr_code_image": "base64_encoded_cropped_qr_image"
}
```

**Note**: `qr_code_image` contains the cropped QR code region as a base64-encoded PNG image with 10% padding around the detected area.

## Error Handling

The function handles:
- Invalid base64 data
- Corrupted images
- Missing QR codes
- Bedrock API errors
- Image cropping failures

All errors are logged and returned with appropriate HTTP status codes.

## Testing Locally

To test locally, you need:
1. Python 3.12
2. Install dependencies: `pip install boto3 pillow`
3. Set environment variables
4. Ensure AWS credentials are configured

## Deployment

The function is deployed via CDK as part of the main stack:
```bash
cd document-insight-extraction
cdk deploy --all --context env=dev
```

The Lambda layer includes pypdf and Pillow for image processing.

## Performance Considerations

- Image size affects processing time
- Claude vision API has rate limits
- Image cropping is fast (<100ms typically)
- Total processing time: 2-10 seconds depending on image complexity
- QR code reading accuracy depends on image quality and QR code complexity

## Security

- All endpoints require Cognito authentication
- Images are processed in memory (not stored)
- Extracted data may contain PII - handle appropriately
- API Gateway throttling applies
