const { MongoClient } = require('mongodb');

const uri = process.env.MONGODB_URI;
const client = new MongoClient(uri);

export default async function handler(req, res) {
    try {
        await client.connect();
        const db = client.db('flexus_data');
        const reviews = await db.collection('reviews')
            .find({})
            .sort({ _id: -1 }) // Mostrar las más recientes primero
            .limit(10)        // Mostrar solo las últimas 10
            .toArray();

        res.status(200).json(reviews);
    } catch (e) {
        res.status(500).json({ error: e.message });
    } finally {
        await client.close();
    }
}
