import { createMailSignalRenderer } from "./mailSignalRenderer";
import type { SignalCommand } from "./mailSignal";

let renderer:ReturnType<typeof createMailSignalRenderer>;
self.onmessage=(event:MessageEvent<SignalCommand>)=>{
  const command=event.data;
  if(command.type==="init") renderer=createMailSignalRenderer(command.canvas);
  else if(command.type==="resize") renderer?.resize(command.size);
  else renderer?.setVisible(command.visible);
};
