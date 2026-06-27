// Auto-generated TypeScript types for Tauri commands

export interface SerialPort {
  port: string;
  description: string;
  hwid: string;
}

// Note: marlin_list_ports returns SerialPort[] directly (not wrapped in MarlinResponse)
// Other commands return void and throw errors on failure

export interface StreamProgress {
  commandsSent: number;
  commandsTotal: number;
  command: string;
  dryRun: boolean;
}

export interface StreamComplete {
  commandsSent: number;
  commandsTotal: number;
}

export interface StreamError {
  code: string;
  message: string;
}

export interface StreamStarted {
  file: string;
  totalCommands: number;
}
