import { useEffect, useState } from 'react';

interface FeatureGroup {
  category: string;
  features: { id: string; name: string; desc: string; link: string }[];
}

export default function FeatureSidebar() {
  const [groups, setGroups] = useState<FeatureGroup[]>([]);

  useEffect(() => {
    fetch('/api/feature_tour.json')
      .then((r) => r.json())
      .then(setGroups)
      .catch(() => setGroups([]));
  }, []);

  return (
    <aside className="border p-2 w-48">
      {groups.map((g) => (
        <div key={g.category} className="mb-2">
          <strong>{g.category}</strong>
          <ul className="ml-2 list-disc">
            {g.features.map((f) => (
              <li key={f.id}>{f.name}</li>
            ))}
          </ul>
        </div>
      ))}
    </aside>
  );
}
