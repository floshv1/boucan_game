// Minimal ambient declarations for the Spotify Web Playback SDK.
// The SDK is loaded at runtime via <script>; strict TS requires these declarations
// to reference window.Spotify without type errors.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export {};

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Spotify?: any;
    onSpotifyWebPlaybackSDKReady?: () => void;
  }
}
