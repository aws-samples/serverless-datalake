import React from 'react';
import { Brain, Clock } from 'lucide-react';

function ThinkingProcess({ thinkingSteps = [] }) {
  if (!thinkingSteps || thinkingSteps.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
      <div className="flex items-center space-x-2 mb-3">
        <Brain className="h-4 w-4 text-gray-600" />
        <span className="text-sm font-medium text-gray-700">Thinking Process</span>
      </div>
      
      <div className="space-y-2">
        {thinkingSteps.map((step, index) => (
          <div key={index} className="flex items-start space-x-3">
            <div className="flex-shrink-0 w-2 h-2 bg-gray-400 rounded-full mt-2"></div>
            <div className="flex-1">
              <p className="text-sm text-gray-600 italic">"{step.content}"</p>
              {step.timestamp && (
                <div className="flex items-center space-x-1 mt-1">
                  <Clock className="h-3 w-3 text-gray-400" />
                  <span className="text-xs text-gray-400">
                    {new Date(step.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ThinkingProcess; 