import React from "react";

const verificationData = [
  {
    label: "Verified",
    value: 78,
    description: "AI verified assets"
  },
  {
    label: "Needs Review",
    value: 12,
    description: "Assets requiring review"
  },
  {
    label: "Failed",
    value: 5,
    description: "Verification failed"
  },
  {
    label: "Processing",
    value: 5,
    description: "Currently processing"
  }
];

function AIVerification() {
  return (
    <div className="ai-verification">

      <div className="section-header">
        <div>
          <h2>AI Verification Summary</h2>

          <p>
            Current status of AI-powered asset verification.
          </p>
        </div>
      </div>

      <div className="verification-grid">

        {verificationData.map((item) => (
          <div className="verification-card" key={item.label}>

            <div className="verification-value">
              {item.value}%
            </div>

            <h3>{item.label}</h3>

            <p>{item.description}</p>

          </div>
        ))}

      </div>

    </div>
  );
}

export default AIVerification;