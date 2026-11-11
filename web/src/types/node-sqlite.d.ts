declare module "node:sqlite" {
  export class DatabaseSync {
    constructor(path: string, options?: { readOnly?: boolean });
    prepare(sql: string): {
      all(...params: Array<string | number>): unknown[];
      get(...params: Array<string | number>): unknown;
    };
  }
}
