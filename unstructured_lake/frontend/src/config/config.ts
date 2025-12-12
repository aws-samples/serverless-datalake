import configData from './config.json';

export interface Config {
  region: string;
  userPoolId: string;
  clientId: string;
  apiUrl: string;
  websocketUrl: string;
}

export const config: Config = configData;

// Function to load config (for compatibility with existing code)
export const loadConfig = async (): Promise<Config> => {
  return config;
};

// Synchronous function to get config (for compatibility with existing code)
export const getConfig = (): Config => {
  return config;
};

export default config;
