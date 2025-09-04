import { useState, useEffect } from "react";
import WorldMap from "./WorldMap";

async function fetchItinerary(country, days, interests) {
  const res = await fetch("http://localhost:8000/generate-itinerary", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ country, days, interests }),
  });

  const data = await res.json();
  return data.itinerary;
}

function ItineraryForm({ countries }) {
  const [country, setCountry] = useState("");
  const [days, setDays] = useState(7);
  const [interests, setInterests] = useState("");
  const [result, setResult] = useState("");

  const handleGenerate = async () => {
    const interestList = interests.split(",").map((i) => i.trim());
    const itinerary = await fetchItinerary(country, days, interestList);
    setResult(itinerary);
  };

  return (
    <div style={{ marginTop: 20 }}>
      <h2>Generate Itinerary</h2>
      <select onChange={(e) => setCountry(e.target.value)} value={country}>
        <option value="">Select a country</option>
        {countries.map((c) => (
          <option key={c.country} value={c.country}>
            {c.country}
          </option>
        ))}
      </select>

      <input
        type="number"
        value={days}
        onChange={(e) => setDays(parseInt(e.target.value))}
        min="1"
        placeholder="Number of days"
      />

      <input
        type="text"
        value={interests}
        onChange={(e) => setInterests(e.target.value)}
        placeholder="Interests (e.g., food, culture)"
      />

      <button onClick={handleGenerate}>Generate</button>

      {result && (
        <div>
          <h3>Itinerary</h3>
          <pre>{result}</pre>
        </div>
      )}
    </div>
  );
}

function App() {
  const [list, setList] = useState(() => {
    const saved = localStorage.getItem("countrySelections");
    return saved ? JSON.parse(saved) : [];
  });

  useEffect(() => {
    localStorage.setItem("countrySelections", JSON.stringify(list));
  }, [list]);

  return (
    <>
      <WorldMap selectionList={list} onSelectionChange={setList} />
      <ItineraryForm countries={list.filter((c) => c.status === "plan")} />
      <pre>{JSON.stringify(list, null, 2)}</pre>
    </>
  );
}

export default App;
