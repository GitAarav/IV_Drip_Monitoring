import React from "react";

export default function SessionSelector({
  sessions,
  selectedSession,
  onChange,
}) {

  return (
    <div className="session-selector">

      <label>
        Demo Session
      </label>

      <select
        value={selectedSession || ""}
        onChange={(e) => onChange(e.target.value)}
      >

        <option value="">
          Select a session
        </option>

        {sessions.map((session) => (

          <option
            key={session.id}
            value={session.id}
          >
            {session.id}
          </option>

        ))}

      </select>

    </div>
  );
}