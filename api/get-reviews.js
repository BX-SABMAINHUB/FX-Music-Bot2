const { MongoClient } = require('mongodb');
const uri = process.env.MONGODB_URI;
const client = new MongoClient(uri);

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    try {
        await client.connect();
        const db = client.db('flexus_data');
        const data = await db.collection('reviews').find({}).sort({ timestamp: -1 }).limit(12).toArray();
        res.status(200).json(data);
    } catch (e) {
        res.status(500).json([]);
    } finally {
        await client.close();
    }
}
