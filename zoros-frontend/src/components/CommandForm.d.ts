export interface CommandSpec {
  command: string;
  params: Array<{
    name: string;
    type: string;
    default?: any;
    required?: boolean;
    help?: string;
  }>;
  [key: string]: any;
}

export function CommandForm(props: { spec: CommandSpec; onRun: (cmd: string, args: Record<string, any>) => void }): JSX.Element; 