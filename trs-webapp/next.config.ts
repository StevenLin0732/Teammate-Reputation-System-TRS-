import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	async rewrites() {
		return [
			{
				source: "/api/:path*",
				destination: "http://127.0.0.1:5328/:path*", // Flask backend
			},
		];
	},
};

export default nextConfig;
