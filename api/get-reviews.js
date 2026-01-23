const { MongoClient } = require('mongodb');

const uri = process.env.MONGODB_URI || "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";
const client = new MongoClient(uri);

export default async function handler(req, res) {
    // Permitir acceso desde cualquier origen
    res.setHeader('Access-Control-Allow-Origin', '*');
    
    try {
        await client.connect();
        const db = client.db('flexus_data');
        const collection = db.collection('reviews');

        // Buscamos reseñas, ordenamos por fecha descendente y limitamos a las 20 mejores
        const reviews = await collection
            .find({})
            .sort({ timestamp: -1 })
            .limit(20)
            .toArray();

        return res.status(200).json(reviews);
    } catch (e) {
        console.error("API ERROR:", e);
        return res.status(500).json([]);
    } finally {
        await client.close();
    }
}
