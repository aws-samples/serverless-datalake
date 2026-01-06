import React from 'react';
import DetectiveHat from './DetectiveHat';
import SmokingPipe from './SmokingPipe';

function CaseFileText() {
  return (
    <div className="evidence-card mb-6 max-w-xl">
      <div className="flex items-center mb-4">
        <DetectiveHat />
        <div className="ml-2">
          <h4 className="font-detective text-lg text-detective-700 mb-1">
            <span className="font-bold uppercase border-b-2 border-detective-accent tracking-wider">CASE FILE:</span>
          </h4>
          <p className="font-detective text-detective-700 tracking-wide leading-relaxed">
            Your data contains valuable secrets waiting to be uncovered.
          </p>
        </div>
      </div>
      
      <div className="flex items-start">
        <SmokingPipe />
        <p className="text-detective-600 font-detective tracking-wide leading-relaxed">
          I'm your investigative partner. Just describe what you're looking for in plain English, and I'll search across all your data sources to find the evidence you need.
        </p>
      </div>
    </div>
  );
}

export default CaseFileText;