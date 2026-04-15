export type InkRenderOptions = {
  stdin: NodeJS.ReadStream;
  stdout: NodeJS.WriteStream;
  stderr: NodeJS.WriteStream;
  exitOnCtrlC: boolean;
  patchConsole: boolean;
};

export function createInkRenderOptions(): InkRenderOptions {
  return {
    stdin: Bun.stdin as unknown as NodeJS.ReadStream,
    stdout: process.stdout,
    stderr: process.stderr,
    exitOnCtrlC: false,
    patchConsole: true,
  };
}
