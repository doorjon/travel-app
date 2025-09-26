import { useState, useEffect, useRef } from "react";
import WorldMap from "./WorldMap";

async function fetchItinerary(country, days, interests, arrivalDate) {
  const res = await fetch("http://localhost:8000/generate-itinerary", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ country, days, interests, arrivalDate }),
  });

  const data = await res.json();
  return data.itinerary;
}

function ItineraryForm({ countries, setResult, setIsModalOpen }) {
  const [country, setCountry] = useState("");
  const [days, setDays] = useState();
  const [interests, setInterests] = useState("");
  const [arrivalDate, setArrivalDate] = useState("");
  //const [result, setResult] = useState("");
  //const [isModalOpen, setIsModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const textareaRef = useRef(null);

  const handleInput = (e) => {
    const el = textareaRef.current;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
    setInterests(e.target.value);
  };

  const handleGenerate = async () => {
    if (!country || !days || !interests.trim()) return;

    setLoading(true);
    const interestList = interests.split(",").map((i) => i.trim());
    try {
      const itinerary = await fetchItinerary(country, days, interestList, arrivalDate);
      setResult(itinerary);
      setIsModalOpen(true);
    } catch (error) {
      console.error("Error generating itinerary:", error);
      // show an error message here
    } finally {
      setLoading(false);
    }
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
        type="date"
        value={arrivalDate}
        onChange={(e) => setArrivalDate(e.target.value)}
      />


      <input
        type="number"
        value={days}
        onChange={(e) => setDays(parseInt(e.target.value))}
        min="1"
        placeholder="Number of days"
      />

      <textarea
        ref={textareaRef}
        value={interests}
        onInput={handleInput}
        placeholder="Interests (e.g. food, history, lighthouses)"
        className="interests-textarea"
        rows={1}
      />

      <button onClick={handleGenerate} disabled={loading}>
        {loading ? "Generating..." : "Generate"}
      </button>

      
    </div>
  );
}

function App() {
  const [list, setList] = useState(() => {
    const saved = localStorage.getItem("countrySelections");
    return saved ? JSON.parse(saved) : [];
  });

  const [isFormVisible, setIsFormVisible] = useState(true);
  const [result, setResult] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);


  useEffect(() => {
    localStorage.setItem("countrySelections", JSON.stringify(list));
  }, [list]);

  const toggleFormVisibility = () => {
    setIsFormVisible(!isFormVisible);
  };

  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(result);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

   const resetAllCountries = () => {
    setList([]);
  };



  return (
    <div className="app-container">
      <WorldMap selectionList={list} onSelectionChange={setList} />
      <div className="form-container">
        <div className={`form-overlay ${isFormVisible ? "visible" : "hidden"}`}>
        <ItineraryForm
          countries={list.filter((c) => c.status === "plan")}
          setResult={setResult}
          setIsModalOpen={setIsModalOpen}
        />

        {/* Reset button */}
        <button onClick={resetAllCountries} style={{ marginTop: "10px" }}>
          Reset Map
        </button>
      </div>


        <div className="form-toggle-button">
          <button onClick={toggleFormVisibility}>
            {isFormVisible ? "←" : "→"}
          </button>
        </div>

        {isModalOpen && (
          <div className="modal-overlay" onClick={() => setIsModalOpen(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button className="modal-close" onClick={() => setIsModalOpen(false)}>×</button>
              <h3>Itinerary</h3>
              <button onClick={handleCopy}>
                {copied ? "Copied!" : "Copy"}
              </button>

              <pre>{result}</pre>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

export default App;
