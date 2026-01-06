import React from 'react';

function SmokingPipe() {
  return (
    <div className="relative w-12 h-12 mr-2">
      {/* Pipe */}
      <svg 
        xmlns="http://www.w3.org/2000/svg" 
        viewBox="0 0 24 24" 
        className="absolute bottom-0 left-0 w-10 h-10 text-detective-700 animate-pipe-glow"
      >
        <path 
          fill="currentColor" 
          d="M20,13H4c-1.1,0-2-0.9-2-2s0.9-2,2-2h16c1.1,0,2,0.9,2,2S21.1,13,20,13z"
        />
        <path 
          fill="currentColor" 
          d="M6,13c-1.7,0-3-1.3-3-3s1.3-3,3-3h2v6H6z"
        />
      </svg>
      
      {/* Animated smoke */}
      <div className="absolute left-1 bottom-6">
        <div className="w-2 h-2 bg-gray-200 rounded-full opacity-0 animate-smoke-1"></div>
      </div>
      <div className="absolute left-2 bottom-7">
        <div className="w-1.5 h-1.5 bg-gray-200 rounded-full opacity-0 animate-smoke-2"></div>
      </div>
      <div className="absolute left-0 bottom-8">
        <div className="w-2.5 h-2.5 bg-gray-200 rounded-full opacity-0 animate-smoke-3"></div>
      </div>
    </div>
  );
}

export default SmokingPipe;