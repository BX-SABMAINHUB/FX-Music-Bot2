const { MongoClient } = require('mongodb');

const uri = process.env.MONGODB_URI || "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";
const client = new MongoClient(uri);

export default async function handler(req, res) {
    // Cabeceras de seguridad y acceso global (CORS)
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET');
    
    try {
        await client.connect();
        const db = client.db('flexus_data');
        const reviews = await db.collection('reviews')
            .find({})
            .sort({ timestamp: -1 })
            .limit(12)
            .toArray();

        res.status(200).json(reviews);
    } catch (e) {
        console.error(e);
        res.status(500).json({ error: "DB_CONNECTION_ERROR" });
    } finally {
        await client.close();
    }
}
