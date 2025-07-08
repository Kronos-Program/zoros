import React, { useEffect, useState } from "react";

export default function FeatureTourWizard() {
  const [data, setData] = useState([]);
  const [step, setStep] = useState(0);

  useEffect(() => {
    fetch("/api/feature_tour.json")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData([]));
  }, []);

  if (!data.length) return <div>Loading...</div>;

  const category = data[step];

  return (
    <div style={{ display: "flex", maxWidth: 900, margin: "0 auto" }}>
      <aside style={{ marginRight: 16 }}>
        {data.map((cat, idx) => (
          <div
            key={cat.category}
            onClick={() => setStep(idx)}
            style={{
              cursor: "pointer",
              padding: "4px 8px",
              background: idx === step ? "var(--accent, #1e90ff)" : "#eee",
              color: idx === step ? "white" : "black",
              marginBottom: 4,
            }}
          >
            {cat.category}
          </div>
        ))}
      </aside>
      <section style={{ flex: 1 }}>
        <h2>{category.category}</h2>
        <ul>
          {category.features.map((f) => (
            <li key={f.id} style={{ marginBottom: 8 }}>
              <strong>{f.name}</strong>: {f.desc}{" "}
              <a href={f.link}>Learn More</a>
            </li>
          ))}
        </ul>
        <div style={{ marginTop: 16 }}>
          <button onClick={() => setStep(Math.max(step - 1, 0))} disabled={step === 0}>
            Back
          </button>
          <button
            onClick={() => setStep(Math.min(step + 1, data.length - 1))}
            disabled={step === data.length - 1}
            style={{ marginLeft: 8 }}
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
