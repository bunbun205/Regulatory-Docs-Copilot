import type { paths } from "./types/api";
import createClient from "openapi-fetch";

const API_KEY_KEY = "labdocs_api_key";

export const getApiKey = () => sessionStorage.getItem(API_KEY_KEY);
export const setApiKey = (key: string) => sessionStorage.setItem(API_KEY_KEY, key);

export const client = createClient<paths>({ baseUrl: "/api" });

export const authenticatedRequest = async <T>(
    req: () => Promise<T>
): Promise<T> => {
    return req();
};
