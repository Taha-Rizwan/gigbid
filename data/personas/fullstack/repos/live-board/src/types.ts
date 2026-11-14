/**
 * Shared type definitions for the dispatch board.
 */
export interface LocationUpdate {
  /** Unique identifier for the truck */
  truckId: string;
  /** Latitude in decimal degrees */
  lat: number;
  /** Longitude in decimal degrees */
  lng: number;
  /** Optional load identifier */
  loadId?: string;
}
