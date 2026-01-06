import React from 'react';
import { CheckCircle, XCircle } from 'lucide-react';

function PlanConfirmationDialog({ plan, onConfirm, onReject }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-medium text-gray-900">Proposed Plan</h3>
        <div className="flex space-x-2">
          <button
            onClick={onConfirm}
            className="flex items-center px-3 py-1 text-sm font-medium text-white bg-green-600 rounded-md hover:bg-green-700"
          >
            <CheckCircle className="h-4 w-4 mr-1" />
            Approve
          </button>
          <button
            onClick={onReject}
            className="flex items-center px-3 py-1 text-sm font-medium text-white bg-red-600 rounded-md hover:bg-red-700"
          >
            <XCircle className="h-4 w-4 mr-1" />
            Reject
          </button>
        </div>
      </div>
      
      <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-3">
        <p className="text-sm text-gray-700 mb-2">
          The orchestrator has prepared a plan to answer your query. Please review and approve or reject:
        </p>
        <div className="space-y-2">
          {plan.map((step, index) => (
            <div key={index} className="flex items-start">
              <div className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-800 rounded-full flex items-center justify-center mr-2 mt-0.5">
                <span className="text-xs font-medium">{step.step_number}</span>
              </div>
              <div>
                <p className="text-sm font-medium text-gray-900">{step.agent_name}</p>
                {step.clarification_message && (
                  <p className="text-sm text-gray-600 italic">"{step.clarification_message}"</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      
      <p className="text-xs text-gray-500">
        Note: Approving will execute the plan. Rejecting will ask the orchestrator to reconsider.
      </p>
    </div>
  );
}

export default PlanConfirmationDialog;