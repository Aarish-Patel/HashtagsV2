/* 
  Configuration File:
  This tells the React Dashboard where to find the Python AI Backend.
*/

// The network address of the Python server (usually 'localhost' if running on the same laptop)
export const API_BASE = 'http://localhost:5000';

// The folder address where incident reports and video clips are stored
export const INCIDENTS_BASE = `${API_BASE}/incidents`;
