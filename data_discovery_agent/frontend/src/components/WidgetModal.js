import React, { useState, useEffect } from 'react';
import { X, BarChart3, Table, TrendingUp } from 'lucide-react';

function WidgetModal({ isOpen, onClose, onSubmit, widget }) {
  const [formData, setFormData] = useState({
    title: '',
    type: 'chart',
    query: '',
    chartType: 'line',
    xAxis: '',
    yAxis: '',
    series: '',
  });

  useEffect(() => {
    if (widget) {
      setFormData({
        title: widget.title || '',
        type: widget.type || 'chart',
        query: widget.query || '',
        chartType: widget.chartData?.type || 'line',
        xAxis: widget.chartData?.xAxis || '',
        yAxis: widget.chartData?.yAxis || '',
        series: widget.chartData?.series?.join(', ') || '',
      });
    } else {
      setFormData({
        title: '',
        type: 'chart',
        query: '',
        chartType: 'line',
        xAxis: '',
        yAxis: '',
        series: '',
      });
    }
  }, [widget]);

  const handleSubmit = (e) => {
    e.preventDefault();
    
    const widgetData = {
      title: formData.title,
      type: formData.type,
      query: formData.query,
    };

    if (formData.type === 'chart') {
      widgetData.chartData = {
        type: formData.chartType,
        xAxis: formData.xAxis,
        yAxis: formData.yAxis,
        series: formData.series.split(',').map(s => s.trim()).filter(Boolean),
      };
    }

    onSubmit(widgetData);
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen pt-4 px-4 pb-20 text-center sm:block sm:p-0">
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity" onClick={onClose} />
        
        <div className="inline-block align-bottom bg-white rounded-lg text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:align-middle sm:max-w-lg sm:w-full">
          <div className="bg-white px-4 pt-5 pb-4 sm:p-6 sm:pb-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-gray-900">
                {widget ? 'Edit Widget' : 'Create Widget'}
              </h3>
              <button
                onClick={onClose}
                className="text-gray-400 hover:text-gray-500"
              >
                <X className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Widget Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Widget Type
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { type: 'chart', icon: BarChart3, label: 'Chart' },
                    { type: 'table', icon: Table, label: 'Table' },
                    { type: 'metric', icon: TrendingUp, label: 'Metric' },
                  ].map(({ type, icon: Icon, label }) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => handleChange('type', type)}
                      className={`p-3 border rounded-lg flex flex-col items-center space-y-2 transition-colors ${
                        formData.type === type
                          ? 'border-primary-500 bg-primary-50 text-primary-700'
                          : 'border-gray-300 hover:border-gray-400'
                      }`}
                    >
                      <Icon className="h-5 w-5" />
                      <span className="text-sm font-medium">{label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Title
                </label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => handleChange('title', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Enter widget title"
                  required
                />
              </div>

              {/* Query */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Data Query
                </label>
                <textarea
                  value={formData.query}
                  onChange={(e) => handleChange('query', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                  placeholder="Enter your data query..."
                  rows="3"
                  required
                />
              </div>

              {/* Chart-specific options */}
              {formData.type === 'chart' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Chart Type
                    </label>
                    <select
                      value={formData.chartType}
                      onChange={(e) => handleChange('chartType', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    >
                      <option value="line">Line Chart</option>
                      <option value="bar">Bar Chart</option>
                      <option value="area">Area Chart</option>
                      <option value="pie">Pie Chart</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        X-Axis Field
                      </label>
                      <input
                        type="text"
                        value={formData.xAxis}
                        onChange={(e) => handleChange('xAxis', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                        placeholder="e.g., date, category"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Y-Axis Field
                      </label>
                      <input
                        type="text"
                        value={formData.yAxis}
                        onChange={(e) => handleChange('yAxis', e.target.value)}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                        placeholder="e.g., value, count"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Series Fields (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={formData.series}
                      onChange={(e) => handleChange('series', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                      placeholder="e.g., sales, revenue, profit"
                    />
                  </div>
                </>
              )}
            </form>
          </div>

          <div className="bg-gray-50 px-4 py-3 sm:px-6 sm:flex sm:flex-row-reverse">
            <button
              type="submit"
              onClick={handleSubmit}
              className="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 bg-primary-600 text-base font-medium text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 sm:ml-3 sm:w-auto sm:text-sm"
            >
              {widget ? 'Update Widget' : 'Create Widget'}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="mt-3 w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default WidgetModal; 