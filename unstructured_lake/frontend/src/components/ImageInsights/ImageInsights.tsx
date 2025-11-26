import React, { useState } from 'react';
import { analyzeImage, type ImageInsightsResponse } from '../../services/api';
import './ImageInsights.css';

const ImageInsights: React.FC = () => {
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>('');
  const [prompt, setPrompt] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');
  const [insights, setInsights] = useState<ImageInsightsResponse | null>(null);

  const handleImageSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (!file.type.startsWith('image/')) {
        setError('Please select a valid image file');
        return;
      }

      setSelectedImage(file);
      setError('');
      setInsights(null);

      // Create preview
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedImage) {
      setError('Please select an image first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Convert image to base64
      const reader = new FileReader();
      reader.onloadend = async () => {
        const base64Image = reader.result as string;

        try {
          const response = await analyzeImage({
            image: base64Image,
            prompt: prompt || undefined,
          });

          setInsights(response);
        } catch (err: any) {
          console.error('Error analyzing image:', err);
          setError(err.response?.data?.error || 'Failed to analyze image');
        } finally {
          setLoading(false);
        }
      };
      reader.readAsDataURL(selectedImage);
    } catch (err) {
      console.error('Error reading image:', err);
      setError('Failed to read image file');
      setLoading(false);
    }
  };

  const handleClear = () => {
    setSelectedImage(null);
    setImagePreview('');
    setPrompt('');
    setInsights(null);
    setError('');
  };

  return (
    <div className="image-insights-container">
      <div className="image-insights-header">
        <h2>Image Insights</h2>
        <p>Upload an image to analyze with Claude vision model</p>
      </div>

      {/* Features Info */}
      <div className="features-info">
        <h3>What can this analyze?</h3>
        <div className="features-grid">
          <div className="feature-item">
            <div className="feature-icon">🔍</div>
            <div className="feature-content">
              <h4>Content Validation</h4>
              <p>Validates image quality and extracts key information like names, ages, and document types</p>
            </div>
          </div>
          <div className="feature-item">
            <div className="feature-icon">🛡️</div>
            <div className="feature-content">
              <h4>Forgery Detection</h4>
              <p>Detects potential image manipulation, deepfakes, and document forgeries with confidence scores</p>
            </div>
          </div>
          <div className="feature-item">
            <div className="feature-icon">📱</div>
            <div className="feature-content">
              <h4>QR Code Detection</h4>
              <p>Automatically detects, reads, and extracts QR codes from images with precise location data</p>
            </div>
          </div>
        </div>
      </div>

      <div className="image-insights-content">
        {/* Upload Section */}
        <div className="upload-section">
          <div className="image-upload-area">
            {imagePreview ? (
              <div className="image-preview">
                <img src={imagePreview} alt="Preview" />
                <button onClick={handleClear} className="clear-button">
                  Clear Image
                </button>
              </div>
            ) : (
              <label className="upload-label">
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleImageSelect}
                  className="file-input"
                />
                <div className="upload-placeholder">
                  <svg
                    className="upload-icon"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <p>Click to upload an image</p>
                  <span>PNG, JPG, JPEG up to 10MB</span>
                </div>
              </label>
            )}
          </div>

          {/* Info Tip */}
          {!selectedImage && (
            <div className="info-tip">
              <div className="tip-icon">💡</div>
              <div className="tip-content">
                <strong>Tip:</strong> Upload images of IDs, documents, or any image containing QR codes for comprehensive analysis including forgery detection.
              </div>
            </div>
          )}

          {/* Prompt Input */}
          <div className="prompt-section">
            <label htmlFor="prompt">Additional Instructions (Optional)</label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="e.g., Focus on detecting specific details, check for authenticity..."
              rows={4}
              disabled={loading}
            />
          </div>

          {/* Analyze Button */}
          <button
            onClick={handleAnalyze}
            disabled={!selectedImage || loading}
            className="analyze-button"
          >
            {loading ? 'Analyzing...' : 'Analyze Image'}
          </button>

          {/* Error Message */}
          {error && <div className="error-message">{error}</div>}
        </div>

        {/* Results Section */}
        {insights && (
          <div className="results-section">
            <h3>Analysis Results</h3>

            {/* Validation Status */}
            <div className="result-card">
              <h4>Image Validation</h4>
              <div className={`status-badge ${insights.is_valid_image ? 'valid' : 'invalid'}`}>
                {insights.is_valid_image ? '✓ Valid Image' : '✗ Invalid Image'}
              </div>
              <p>{insights.validation_message}</p>
            </div>

            {/* Key Insights */}
            {insights.key_insights && Object.keys(insights.key_insights).length > 0 && (
              <div className="result-card">
                <h4>Key Insights</h4>
                <div className="insights-grid">
                  {insights.key_insights.name && (
                    <div className="insight-item">
                      <span className="insight-label">Name:</span>
                      <span className="insight-value">{insights.key_insights.name}</span>
                    </div>
                  )}
                  {insights.key_insights.age && (
                    <div className="insight-item">
                      <span className="insight-label">Age:</span>
                      <span className="insight-value">{insights.key_insights.age}</span>
                    </div>
                  )}
                  {insights.key_insights.document_type && (
                    <div className="insight-item">
                      <span className="insight-label">Document Type:</span>
                      <span className="insight-value">{insights.key_insights.document_type}</span>
                    </div>
                  )}
                  {insights.key_insights.other_details && insights.key_insights.other_details.length > 0 && (
                    <div className="insight-item full-width">
                      <span className="insight-label">Other Details:</span>
                      <ul className="details-list">
                        {insights.key_insights.other_details.map((detail, index) => (
                          <li key={index}>{detail}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Forgery Detection */}
            <div className="result-card">
              <h4>Forgery Detection</h4>
              <div className={`status-badge ${insights.forgery_detection.suspicious ? 'suspicious' : 'clean'}`}>
                {insights.forgery_detection.suspicious ? '⚠ Suspicious' : '✓ No Issues Detected'}
              </div>
              <div className="confidence-bar">
                <span>Confidence: {(insights.forgery_detection.confidence * 100).toFixed(1)}%</span>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${insights.forgery_detection.confidence * 100}%` }}
                  />
                </div>
              </div>
              {insights.forgery_detection.indicators && insights.forgery_detection.indicators.length > 0 && (
                <div className="indicators">
                  <strong>Indicators:</strong>
                  <ul>
                    {insights.forgery_detection.indicators.map((indicator, index) => (
                      <li key={index}>{indicator}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* QR Code Detection */}
            <div className="result-card">
              <h4>QR Code Detection</h4>
              <div className={`status-badge ${insights.qr_code_detected ? 'detected' : 'not-detected'}`}>
                {insights.qr_code_detected ? '✓ QR Code Detected' : 'No QR Code Found'}
              </div>
              {insights.qr_code_detected && (
                <div className="qr-info">
                  {insights.qr_bounding_box && (
                    <>
                      <p>
                        <strong>Location:</strong> x: {insights.qr_bounding_box.x}, y: {insights.qr_bounding_box.y}
                      </p>
                      <p>
                        <strong>Size:</strong> {insights.qr_bounding_box.width} × {insights.qr_bounding_box.height}
                      </p>
                    </>
                  )}
                  {insights.qr_code_data && (
                    <div className="qr-data">
                      <strong>Decoded Data:</strong>
                      <pre>{insights.qr_code_data}</pre>
                    </div>
                  )}
                  {insights.qr_code_image && (
                    <div className="qr-image-preview">
                      <strong>Cropped QR Code:</strong>
                      <img 
                        src={`data:image/png;base64,${insights.qr_code_image}`} 
                        alt="Cropped QR Code" 
                        className="qr-code-image"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Raw Response (if available) */}
            {insights.raw_response && (
              <div className="result-card">
                <h4>Raw Analysis</h4>
                <pre className="raw-response">{insights.raw_response}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ImageInsights;
