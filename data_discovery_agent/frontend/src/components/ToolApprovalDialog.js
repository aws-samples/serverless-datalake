import React from 'react';
import { CheckCircle, XCircle, Shield, AlertTriangle, Info } from 'lucide-react';

function ToolApprovalDialog({ approvalData, onApprove, onDeny, onAlwaysApprove }) {
  const { reason, agent_name, query } = approvalData;
  
  // Get risk level styling
  const getRiskLevelStyle = (riskLevel) => {
    switch (riskLevel?.toLowerCase()) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getRiskIcon = (riskLevel) => {
    switch (riskLevel?.toLowerCase()) {
      case 'high':
        return <AlertTriangle className="h-4 w-4" />;
      case 'medium':
        return <Shield className="h-4 w-4" />;
      case 'low':
        return <Info className="h-4 w-4" />;
      default:
        return <Shield className="h-4 w-4" />;
    }
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Shield className="h-5 w-5 text-blue-600" />
          <h3 className="text-lg font-medium text-gray-900">Tool Approval Required</h3>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={onApprove}
            className="flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
          >
            <CheckCircle className="h-4 w-4 mr-1" />
            Approve
          </button>
          <button
            onClick={onAlwaysApprove}
            className="flex items-center px-3 py-1 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700"
          >
            <CheckCircle className="h-4 w-4 mr-1" />
            Always Approve
          </button>
          <button
            onClick={onDeny}
            className="flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
          >
            <XCircle className="h-4 w-4 mr-1" />
            Deny
          </button>
        </div>
      </div>
      
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-3">
        <p className="text-sm text-gray-700 mb-3">
          The <strong>{agent_name}</strong> agent is requesting permission to execute a tool operation. Please review the details below:
        </p>
        
        {/* Service and Operation Info */}
        {(reason?.service || reason?.operation) && (
          <div className="grid grid-cols-2 gap-4 mb-3">
            {reason?.service && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Service</p>
                <p className="text-sm font-medium text-gray-900">{reason.service}</p>
              </div>
            )}
            {reason?.operation && (
              <div>
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Operation</p>
                <p className="text-sm font-medium text-gray-900">{reason.operation}</p>
              </div>
            )}
          </div>
        )}

        {/* Risk Level */}
        {reason?.risk_level && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Risk Level</p>
            <div className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium border ${getRiskLevelStyle(reason.risk_level)}`}>
              {getRiskIcon(reason.risk_level)}
              <span className="ml-1">{reason.risk_level.toUpperCase()}</span>
            </div>
          </div>
        )}

        {/* Tool Name */}
        {reason?.tool_name && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Tool</p>
            <p className="text-sm font-mono text-gray-800 bg-gray-100 px-2 py-1 rounded">{reason.tool_name}</p>
          </div>
        )}

        {/* Summary */}
        {reason?.summary && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Summary</p>
            <p className="text-sm text-gray-700">{reason.summary}</p>
          </div>
        )}

        {/* Tool Parameters */}
        {reason?.tool_parameters && Object.keys(reason.tool_parameters).length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Tool Parameters</p>
            <div className="bg-blue-50 border border-blue-200 rounded p-3">
              {Object.entries(reason.tool_parameters).map(([key, value]) => (
                <div key={key} className="flex flex-col sm:flex-row sm:justify-between py-1 border-b border-blue-100 last:border-b-0">
                  <span className="text-xs font-medium text-blue-700 mb-1 sm:mb-0">{key}:</span>
                  <span className="text-xs text-blue-800 font-mono bg-white px-2 py-1 rounded max-w-xs break-all">
                    {typeof value === 'string' && value.length > 100 
                      ? `${value.substring(0, 100)}...` 
                      : JSON.stringify(value)
                    }
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Tool Input (alternative to tool_parameters) */}
        {/* {reason?.tool_input && Object.keys(reason.tool_input).length > 0 && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Tool Input</p>
            <div className="bg-green-50 border border-green-200 rounded p-3">
              {Object.entries(reason.tool_input).map(([key, value]) => (
                <div key={key} className="flex flex-col sm:flex-row sm:justify-between py-1 border-b border-green-100 last:border-b-0">
                  <span className="text-xs font-medium text-green-700 mb-1 sm:mb-0">{key}:</span>
                  <span className="text-xs text-green-800 font-mono bg-white px-2 py-1 rounded max-w-xs break-all">
                    {typeof value === 'string' && value.length > 100 
                      ? `${value.substring(0, 100)}...` 
                      : JSON.stringify(value)
                    }
                  </span>
                </div>
              ))}
            </div>
          </div>
        )} */}

        {/* Debug: Show all reason data */}
        {/* {process.env.NODE_ENV === 'development' && (
          <div className="mb-3">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Debug: Reason Data</p>
            <div className="bg-gray-100 border border-gray-300 rounded p-2">
              <pre className="text-xs text-gray-800 whitespace-pre-wrap">
                {JSON.stringify(reason, null, 2)}
              </pre>
            </div>
          </div>
        )} */}
      </div>
      
      <div className="flex items-start space-x-2 text-xs text-gray-500">
        <Info className="h-4 w-4 mt-0.5 flex-shrink-0" />
        <div>
          <p><strong>Approve:</strong> Execute this operation once</p>
          <p><strong>Always Approve:</strong> Remember this decision for similar operations</p>
          <p><strong>Deny:</strong> Cancel this operation and continue without it</p>
        </div>
      </div>
    </div>
  );
}

export default ToolApprovalDialog;