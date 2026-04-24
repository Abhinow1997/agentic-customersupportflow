declare global {
  namespace App {
    interface PublicEnv {
      PUBLIC_FASTAPI_URL: string;
    }
  }
}

export {};