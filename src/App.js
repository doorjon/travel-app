import { useState, useEffect } from "react";
import WorldMap from "./WorldMap";

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
      <pre>{JSON.stringify(list, null, 2)}</pre>
    </>
  );
}

export default App;
