import { PUBLIC_FASTAPI_URL } from '$env/static/public';

export const FASTAPI_URL = PUBLIC_FASTAPI_URL.replace(/\/+$/, '');
