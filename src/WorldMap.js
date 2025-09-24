import { useState, useRef, useEffect } from "react";
import { MapContainer, TileLayer, GeoJSON, useMap } from "react-leaflet";
import L from "leaflet";
import worldGeo from "./world.geo.json";
import "leaflet/dist/leaflet.css";

const COLOUR_VISITED  = "#1b9e77";
const COLOUR_PLAN     = "#d95f02";
const COLOUR_DEFAULT  = "#ffffff";

function useClickPopup() {
  const map = useMap();
  const popupRef = useRef(null);

  const open = (latlng, onChoice) => {
    if (popupRef.current) map.closePopup(popupRef.current);

    const html = `
  <div style="font-size:13px">
    <button class="popup-btn" data-choice="visited">Visited</button>
    <button class="popup-btn" data-choice="plan">Plan to visit</button>
    <button class="popup-btn" data-choice="reset">Reset</button>
  </div>`;


    popupRef.current = L.popup()
      .setLatLng(latlng)
      .setContent(html)
      .openOn(map);

    setTimeout(() => {
      document.querySelectorAll(".popup-btn").forEach((btn) =>
        btn.addEventListener("click", (e) => {
          const choice = e.target.dataset.choice;
          onChoice(choice);
          map.closePopup(popupRef.current);
          popupRef.current = null;
        })
      );
    }, 10);
  };

  return open;
}

function InteractiveCountries({ selectionList, onChange }) {
  const [choices, setChoices] = useState({});

  const openPopup = useClickPopup();

  useEffect(() => {
    const initial = {};
    selectionList.forEach(({ country, status }) => {
      initial[country] = status;
    });
    setChoices(initial);
  }, [selectionList]);

  const handleClick = (e, countryName) => {
    openPopup(e.latlng, (status) => {
      let next = { ...choices };

      if (status === "none") {
        delete next[countryName];
      } else {
        next[countryName] = status;
      }

      setChoices(next);

      const formattedList = Object.entries(next).map(([country, status]) => ({
        country,
        status,
      }));
      onChange(formattedList);

    });
  };

  const style = (feature) => {
    const status = choices[feature.properties.name];
    const fill =
      status === "visited"
        ? COLOUR_VISITED
        : status === "plan"
        ? COLOUR_PLAN
        : COLOUR_DEFAULT;

    return {
      fillColor: fill,
      weight: 1,
      opacity: 1,
      color: "#666",
      fillOpacity: 0.8,
    };
  };

  return (
    <>
      {worldGeo.features.map((feature) => {
        const name = feature.properties.name;
        return (
          <GeoJSON
            key={name}
            data={feature}
            style={style}
            eventHandlers={{
              click: (e) => handleClick(e, name),
            }}
          />
        );
      })}
    </>
  );
}


export default function WorldMap({ selectionList, onSelectionChange }) {
  return (
    <MapContainer
      center={[20, 0]}
      zoom={2}
      minZoom={2}
      style={{ height: "100%", width: "100%" }}
    >

      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
      />
      <InteractiveCountries
        selectionList={selectionList}
        onChange={onSelectionChange}
      />
    </MapContainer>
  );
}

