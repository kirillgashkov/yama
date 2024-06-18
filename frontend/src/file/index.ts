import { ApiError, useApiService } from "@/api";

export enum FileType {
  REGULAR = "regular",
  DIRECTORY = "directory",
}

export interface RegularContentOut {
  url: string;
}

export interface RegularOut {
  id: string;
  type: FileType.REGULAR;
  content?: RegularContentOut | null;
}

export interface DirectoryContentFileOut {
  name: string;
  file: FileOut;
}

export interface DirectoryContentOut {
  files: DirectoryContentFileOut[];
}

export interface DirectoryOut {
  id: string;
  type: FileType.DIRECTORY;
  content?: DirectoryContentOut | null;
}

export type FileOut = RegularOut | DirectoryOut;
export type FileContentOut = RegularContentOut | DirectoryContentOut;

export function useFileService() {
  const api = useApiService();

  return {
    async read(
      path: string,
      options: { workingFileId?: string } = {},
    ): Promise<FileOut> {
      const f = (await api.get((url) => {
        const u = new URL(url);
        u.pathname = "/files/" + path;
        if (options.workingFileId) {
          u.searchParams.append("working_file_id", options.workingFileId);
        }
        return u;
      })) as FileOut;

      return f;
    },
    async readContent(
      path: string,
      options: { workingFileId?: string } = {},
    ): Promise<string> {
      const r = await api.getAsResponse((url) => {
        const u = new URL(url);
        u.pathname = "/files/" + path;
        u.searchParams.append("content", "1");
        if (options.workingFileId) {
          u.searchParams.append("working_file_id", options.workingFileId);
        }
        return u;
      });

      return r.text();
    },
  };
}
