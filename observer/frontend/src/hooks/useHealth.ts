import { useEffect, useState } from 'react';

export function useHealth(): boolean | null {
  const [providerConnected, setProviderConnected] = useState<boolean | null>(null);

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then((data) => setProviderConnected(data?.provider?.connected ?? false))
      .catch(() => setProviderConnected(false));
  }, []);

  return providerConnected;
}
