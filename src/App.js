// App.js
import { useState } from "react";
import WorldMap from "./WorldMap";

function App() {
  const [list, setList] = useState([]);

  return (
    <>
      <WorldMap onSelectionChange={setList} />
      <pre>{JSON.stringify(list, null, 2)}</pre>
    </>
  );
}

export default App;