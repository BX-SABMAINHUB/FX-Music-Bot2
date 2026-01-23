const { MongoClient } = require('mongodb');

const uri = process.env.MONGODB_URI || "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";
const client = new MongoClient(uri);

export default async function handler(req, res) {
    try {
        await client.connect();
        const db = client.db('flexus_data');
        const reviewsCol = db.collection('reviews');

        // Buscamos las últimas 20 reseñas ordenadas por fecha (timestamp)
        const reviews = await reviewsCol
            .find({})
            .sort({ timestamp: -1 }) 
            .limit(20)
            .toArray();

        // Respondemos con los datos
        res.status(200).json(reviews);
    } catch (e) {
        console.error("Error en API Reviews:", e);
        res.status(500).json({ error: "No se pudieron cargar las reseñas", details: e.message });
    } finally {
        await client.close();
    }
}
