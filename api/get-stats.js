const { MongoClient } = require('mongodb');

const uri = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";
let cachedDb = null;

async function connectToDatabase() {
    if (cachedDb) return cachedDb;
    const client = await MongoClient.connect(uri);
    const db = client.db("flexus_data");
    cachedDb = db;
    return db;
}

export default async function handler(req, res) {
    // IMPORTANTE: Permitir que cualquier web lo lea
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store, max-age=0');

    try {
        const db = await connectToDatabase();
        const stats = await db.collection("ads_stats").findOne({ id: "global" });
        
        res.status(200).json({ views: stats ? stats.views : 0 });
    } catch (error) {
        console.error("Error en MongoDB:", error);
        res.status(500).json({ error: "Fallo al conectar con la base de datos" });
    }
}
