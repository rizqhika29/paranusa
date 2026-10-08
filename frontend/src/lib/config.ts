// ParaNusa network config, explorer links, location presets & triggers.

export type NetworkKey = "studionet" | "bradbury" | "localnet";

export interface NetworkConfig {
  key: NetworkKey;
  label: string;
  chainId: number;
  rpc: string;
  explorerTx: (hash: string) => string | null;
  explorerContract: (address: string) => string | null;
  faucetHint: string;
}

export const NETWORKS: Record<NetworkKey, NetworkConfig> = {
  studionet: {
    key: "studionet",
    label: "Studionet",
    chainId: 61999,
    rpc: "https://studio.genlayer.com/api",
    explorerTx: (h) => `https://explorer-studio.genlayer.com/tx/${h}`,
    explorerContract: (a) => `https://explorer-studio.genlayer.com/contracts/${a}`,
    faucetHint: "Get test GEN via the GenLayer Discord / Studio faucet.",
  },
  bradbury: {
    key: "bradbury",
    label: "Bradbury Testnet",
    chainId: 4221,
    rpc: "https://rpc-bradbury.genlayer.com",
    explorerTx: (h) => `https://explorer-bradbury.genlayer.com/tx/${h}`,
    explorerContract: (a) => `https://explorer-bradbury.genlayer.com/contracts/${a}`,
    faucetHint: "Get Bradbury GEN from the official GenLayer faucet.",
  },
  localnet: {
    key: "localnet",
    label: "Localnet (glsim)",
    chainId: 61127,
    rpc: "http://127.0.0.1:4000/api",
    explorerTx: () => null,
    explorerContract: () => null,
    faucetHint: "glsim funds test accounts automatically.",
  },
};

export type DisasterType = "drought" | "flood" | "earthquake";

export interface LocationPreset {
  id: string;
  name: string;
  lat: string;
  lon: string;
  disaster: DisasterType;
  threshold: string;
  unit: string;
  blurb: string;
}

export const LOCATION_PRESETS: LocationPreset[] = [
  {
    id: "grobogan",
    name: "Grobogan, Central Java",
    lat: "-7.0",
    lon: "110.6",
    disaster: "drought",
    threshold: "20.0",
    unit: "mm / 30 days",
    blurb: "A rice belt hit by drought almost every dry season.",
  },
  {
    id: "karawang",
    name: "Karawang, West Java",
    lat: "-6.3",
    lon: "107.3",
    disaster: "drought",
    threshold: "20.0",
    unit: "mm / 30 days",
    blurb: "Rice granary — harvests fail when rains arrive late.",
  },
  {
    id: "jakarta",
    name: "North Jakarta, DKI Jakarta",
    lat: "-6.2",
    lon: "106.8",
    disaster: "flood",
    threshold: "150.0",
    unit: "mm / 7 days",
    blurb: "Tidal floods + extreme rain — needs fast post-flood payouts.",
  },
  {
    id: "cianjur",
    name: "Cianjur, West Java",
    lat: "-6.8",
    lon: "107.1",
    disaster: "earthquake",
    threshold: "5.0",
    unit: "magnitude (M)",
    blurb: "Active fault zone — automatic payout on damaging quakes.",
  },
];

export const DISASTER_META: Record<
  DisasterType,
  { label: string; color: string; unit: string; source: string; tolerance: string }
> = {
  drought: {
    label: "Drought",
    color: "#F5A524",
    unit: "mm / 30 days (total rain < threshold)",
    source: "Open-Meteo · precipitation_sum, past_days=30",
    tolerance: "Consensus tolerance ±2.0 mm",
  },
  flood: {
    label: "Flood",
    color: "#38BDF8",
    unit: "mm / 7 days (total rain > threshold)",
    source: "Open-Meteo · precipitation_sum, past_days=7",
    tolerance: "Consensus tolerance ±2.0 mm",
  },
  earthquake: {
    label: "Earthquake",
    color: "#E4572E",
    unit: "Max magnitude within 200 km (≥ threshold)",
    source: "USGS Earthquake Catalog · GeoJSON",
    tolerance: "Consensus tolerance ±0.3 M",
  },
};

export function contractAddressFor(network: NetworkKey): string {
  if (network === "studionet")
    return process.env.NEXT_PUBLIC_CONTRACT_STUDIONET ?? "";
  if (network === "bradbury")
    return process.env.NEXT_PUBLIC_CONTRACT_BRADBURY ?? "";
  return process.env.NEXT_PUBLIC_CONTRACT_LOCALNET ?? "";
}

export function isZeroAddress(addr: string): boolean {
  return !addr || /^0x0+$/.test(addr.trim().toLowerCase());
}
