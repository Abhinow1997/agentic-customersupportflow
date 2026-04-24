import { PUBLIC_FASTAPI_URL } from '$env/static/public';

export const PUBLIC_FASTAPI_URL_NORMALIZED = PUBLIC_FASTAPI_URL.replace(/\/+$/, '');
export const FASTAPI_URL = PUBLIC_FASTAPI_URL_NORMALIZED;
