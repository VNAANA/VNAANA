
module.exports = {
    ci: {
        collect: {
            startServerCommand:
                'pnpm preview --host 127.0.0.1 --port 4173 --strictPort',
            startServerReadyPattern: 'Local:.*127\\.0\\.0\\.1:4173',
            startServerReadyTimeout: 60000,

            url: ['http://127.0.0.1:4173/'],
            numberOfRuns: 3,
        },

        assert: {
            assertions: {
                'categories:performance': [
                    'warn',
                    { minScore: 0.80 },
                ],
                'first-contentful-paint': [
                    'warn',
                    { maxNumericValue: 1800 },
                ],
                'largest-contentful-paint': [
                    'warn',
                    { maxNumericValue: 2500 },
                ],
                'total-blocking-time': [
                    'warn',
                    { maxNumericValue: 200 },
                ],
                'cumulative-layout-shift': [
                    'warn',
                    { maxNumericValue: 0.1 },
                ],
            },
        },

        upload: {
            target: 'filesystem',
            outputDir: './.lighthouseci',
        },
    },
}
